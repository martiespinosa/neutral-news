//
//  ContentView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import SwiftUI

struct HomeView: View {
    @State private var vm = ViewModel()
    @State private var date: Date = Date.now
    
    @Namespace private var animationNamespace
    
    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack {
                    ForEach(vm.filteredNews) { neutralNews in
                        NavigationLink {
                            NeutralNewsView(news: neutralNews, relatedNews: vm.getRelatedNews(from: neutralNews), namespace: animationNamespace)
                                .navigationTransition(.zoom(sourceID: neutralNews.id, in: animationNamespace))
                        } label: {
                            NewsImageView(news: neutralNews, imageUrl: neutralNews.imageUrl)
                                .padding(.vertical, 4)
                                .matchedTransitionSource(id: neutralNews.id, in: animationNamespace)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal)
            }
            .refreshable {
                vm.fetchNeutralNewsFromFirestore()
                vm.fetchNewsFromFirestore()
            }
            .navigationTitle("Hoy")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { filterMenu }
            }
        }
    }
    
    var filterMenu: some View {
        Menu {
            Menu("Medio") {
                ForEach(Media.allCases, id: \.self) { media in
                    Button {
                        vm.filterByMedium(media)
                    } label: {
                        Label {
                            Text(media.pressMedia.name)
                        } icon: {
                            if vm.mediaFilter.contains(media) {
                                Image(systemName: "checkmark")
                            }
                        }
                    }

                }
            }
            Menu("Categoria") {
                ForEach(Category.allCases, id: \.self) { category in
                    Button {
                        vm.filterByCategory(category)
                    } label: {
                        Label {
                            Text(category.rawValue)
                        } icon: {
                            if vm.categoryFilter.contains(category) {
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                }
            }
            
            if vm.isAnyFilterEnabled {
                Section {
                    Button("Limpiar Filtros", role: .destructive) {
                        vm.mediaFilter.removeAll()
                        vm.categoryFilter.removeAll()
                        vm.filteredNews = vm.neutralNews
                    }
                }
            }
        } label: {
            Label("Filtrar", systemImage: vm.isAnyFilterEnabled ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
        }
    }
}

#Preview {
    HomeView()
}
